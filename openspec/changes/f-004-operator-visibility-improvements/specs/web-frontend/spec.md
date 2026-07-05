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
