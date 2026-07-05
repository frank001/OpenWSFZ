## ADDED Requirements

### Requirement: TX panel — Call CQ button

The TX panel SHALL contain a single `<button id="tx-call-cq-btn">` whose label, enabled state, and
click action are all derived from the existing `role` and `state` fields (no additional
server-side signal beyond the new `POST /api/v1/tx/stop-cq` endpoint described below):

| Condition | Enabled? | Label | Click action |
|---|---|---|---|
| `role !== "caller"` and `state === "Idle"` | Enabled | "Call CQ" | `POST /api/v1/tx/call-cq` (existing) |
| `role === "caller"` and `state !== "Idle"` | Enabled | "Stop CQ" | `POST /api/v1/tx/stop-cq` (new) |
| `role !== "caller"` and `state !== "Idle"` (answerer mid-QSO) | Disabled | "Call CQ" | — |

This SHALL supersede the button's previous informal gating (`disabled` whenever `state !== "Idle"`,
undocumented as a formal requirement prior to this change) — the button is no longer unconditionally
disabled for the whole non-`Idle` duration of a caller session; while `role === "caller"` it remains
enabled throughout, so the operator can always stop a session in progress.

A "Stop CQ" click requests a **graceful stop**, distinct from the always-available `Abort TX`
button: any TX sample already in flight plays to completion (no audio interruption), and the
service returns to `Idle` only once it reaches its next natural wait point. The click handler
SHALL NOT re-render the panel from the `POST /api/v1/tx/stop-cq` response directly — the panel
SHALL update once the subsequent `txState` WebSocket event carrying `state: "Idle"` arrives,
consistent with how `Abort TX` is already handled.

This button's bright-green "engaged" colour while `role === "caller" && autoAnswerEnabled` is
governed by the `tx-state-indicators` capability, independently of the enabled/label/click
behaviour specified here.

#### Scenario: Idle button starts a CQ session

- **WHEN** `state` is `"Idle"` (any role)
- **THEN** `#tx-call-cq-btn` SHALL be enabled with label "Call CQ"
- **AND** clicking it SHALL call `POST /api/v1/tx/call-cq`

#### Scenario: Engaged caller button offers a graceful stop

- **WHEN** `role` is `"caller"` and `state` is any non-`"Idle"` value (e.g. `"TxCq"`,
  `"WaitAnswer"`, `"TxReport"`, `"WaitRr73"`, `"TxRr73"`, `"QsoComplete"`)
- **THEN** `#tx-call-cq-btn` SHALL be enabled with label "Stop CQ"
- **AND** clicking it SHALL call `POST /api/v1/tx/stop-cq`, not `POST /api/v1/tx/abort`

#### Scenario: Answerer mid-QSO disables the button

- **WHEN** `role` is `"answerer"` and `state` is not `"Idle"`
- **THEN** `#tx-call-cq-btn` SHALL be disabled with label "Call CQ"

#### Scenario: Stop CQ click does not immediately re-render the panel

- **WHEN** the operator clicks "Stop CQ" and `POST /api/v1/tx/stop-cq` returns HTTP 200 with a
  non-`"Idle"` `state` (TX still completing)
- **THEN** the TX panel SHALL NOT be forced to the `Idle`/disarmed appearance from that response
  alone
- **AND** the panel SHALL update to `Idle` only when a subsequent `txState` WebSocket event with
  `state: "Idle"` is received

#### Scenario: Clicking Stop CQ twice in quick succession is idempotent

- **WHEN** `POST /api/v1/tx/stop-cq` is sent twice in immediate succession for the same session
- **THEN** neither call SHALL error, and the service SHALL still reach `Idle` exactly once, at the
  same point it would have from a single request

---

## MODIFIED Requirements

### Requirement: TX panel — Enable TX toggle button

The TX panel SHALL contain a single `<button id="tx-enable-btn">` that reflects and
controls the `tx.autoAnswer` state:

- **Disarmed** (`autoAnswer = false`): label reads **"Enable TX"**; standard neutral
  button styling.
- **Armed** (`autoAnswer = true`): label reads **"Enable TX"** (label does not change);
  the button SHALL have a visually alarming style (red/danger background, bold weight)
  so the operator cannot overlook that autonomous transmission is active. The label is
  intentionally kept as "Enable TX" in both states; a visually alarming colour alone
  signals the armed condition (D-TX-UI-002 — UAT decision 2026-06-22). The specific
  armed-state colour — dark red when not currently transmitting, bright red when the
  `txState` payload's `state` is one of the transmitting `Tx*` sub-states — is governed
  by the `tx-state-indicators` capability; this requirement establishes only that an
  armed style distinct from the disarmed style SHALL always be present.

Clicking the button in the disarmed state SHALL call `POST /api/v1/tx/enable` and
apply an armed CSS class on HTTP 200. Clicking in the armed state SHALL call
`POST /api/v1/tx/disable` and remove all armed CSS classes on HTTP 200. The button
SHALL be disabled for the duration of the pending request.

#### Scenario: Button shows Enable TX and is disarmed when autoAnswer is false

- **WHEN** the page loads and `GET /api/v1/tx/status` returns `autoAnswerEnabled: false`
- **THEN** `#tx-enable-btn` SHALL have text content "Enable TX"
- **AND** SHALL NOT have the `tx-btn-armed` or `tx-btn-transmitting` CSS class

#### Scenario: Button shows Enable TX with armed style when autoAnswer is true

- **WHEN** the page loads and `GET /api/v1/tx/status` returns `autoAnswerEnabled: true`
- **THEN** `#tx-enable-btn` SHALL have text content "Enable TX"
- **AND** SHALL have an armed CSS class applied (`tx-btn-armed` or `tx-btn-transmitting`,
  per the `state` value — see `tx-state-indicators`)

#### Scenario: Clicking Enable TX (disarmed) calls /tx/enable and applies armed style

- **WHEN** `#tx-enable-btn` is clicked while in the disarmed state
- **THEN** `POST /api/v1/tx/enable` SHALL be called
- **AND** on HTTP 200, an armed CSS class SHALL be applied; label remains "Enable TX"

#### Scenario: Clicking Enable TX (armed) calls /tx/disable and removes armed style

- **WHEN** `#tx-enable-btn` is clicked while in the armed state
- **THEN** `POST /api/v1/tx/disable` SHALL be called
- **AND** on HTTP 200, all armed CSS classes SHALL be removed; label remains "Enable TX"

#### Scenario: Button is disabled during pending request

- **WHEN** a click on `#tx-enable-btn` triggers a request that has not yet resolved
- **THEN** `#tx-enable-btn` SHALL be `disabled` until the response (success or error) is
  received
